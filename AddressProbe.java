// SPDX-License-Identifier: GPL-3.0-only
import java.io.*;
import net.osmand.binary.*;
import net.osmand.binary.BinaryMapAddressReaderAdapter.CityBlocks;
import net.osmand.data.*;
class AddressProbe {
 static String norm(String s){return s.toLowerCase().replaceAll("\\bstreet\\b","st").replaceAll("\\blane\\b","ln").replaceAll("\\broad\\b","rd").replaceAll("\\bnorth\\b","n").replaceAll("\\bsouth\\b","s").replaceAll("\\beast\\b","e").replaceAll("\\bwest\\b","w").replaceAll("[^a-z0-9]","");}
 public static void main(String[] a)throws Exception{
 File f=new File(a[0]);var r=new BinaryMapIndexReader(new RandomAccessFile(f,"r"),f);try{
 if(a.length==1)return;
 int cities=0,streets=0,buildings=0,matches=0;
 for(var block:new CityBlocks[]{CityBlocks.CITY_TOWN_TYPE,CityBlocks.VILLAGES_TYPE})for(City c:r.getCities(null,block))if(c.getName().equalsIgnoreCase(a[1])){
 cities++;r.preloadStreets(c,null,null);
 for(Street s:c.getStreets())if(norm(s.getName()).equals(norm(a[2]))){
 streets++; if(s.getLocation()!=null)System.out.println("STREET\t"+s.getName()+", "+c.getName()+"\t"+s.getLocation().getLatitude()+"\t"+s.getLocation().getLongitude());
 r.preloadBuildings(s,null,null);
 for(Building b:s.getBuildings()){buildings++;
 if(!a[3].isEmpty() && b.getName().equalsIgnoreCase(a[3]) && b.getLocation()!=null){matches++;System.out.println("MATCH\tbuilding\t"+b.getLocation().getLatitude()+"\t"+b.getLocation().getLongitude());}
 else if(!a[3].isEmpty() && b.belongsToInterpolation(a[3]) && b.getLatLon2()!=null){var p=b.getLocation(b.interpolation(a[3]));if(p!=null)System.out.println("INTERPOLATION\t"+b.getName()+"–"+b.getName2()+"\t"+p.getLatitude()+"\t"+p.getLongitude());}
 }
 }
 }
 System.out.println("COUNTS\t"+cities+"\t"+streets+"\t"+buildings+"\t"+matches);
 }finally{r.close();}
 }
}
